"""
Usage: python remove_obsolete_test_inheritance.py <project path> <class reference cutoff> <test case indicator class names>


reduce test code automatically...
through checking obsolete test class inheritance

needed tools:
* walk through all test areas...
* MRO inspection (all methods of all super-superclasses)
* inspect
* pick next super class
* run current test class
* drop it from superclasses list
* run current test class
    * get current class reference
* check os exit code
* git revert
* git commit + push

procedure:
walk through every test module...
through every class definition there...

if superclass
	is TestCase or PaesslerTestCase:
		continue  with next superclass

	has "def test" or inherits "def test"
		dont touch it
		pick next super class
	else
		drop it from superclasses list
		run current test class
			if tests fail
				revert changes
			else
				commit + push changes
				pick next super class
"""
import sys
from git import Repo, Git
import os
import re
import subprocess
from glob import glob
import pyclbr


SUPER_CLASSES_RE = r"^class\s{class_name}\((?P<super>(\w|\,|\.|\s)*)\)\:"
all_classes_by_names = dict()
test_case_names_by_inheritance = set()
test_case_names_by_method_def = set()
all_test_case_names = set()


def find_test_modules(root_path, search_pattern='test*.py'):
    return [
        cur_module_path
        for cur_dir_tree in os.walk(root_path)
        for cur_module_path in
        glob(os.path.join(cur_dir_tree[0], search_pattern))
    ]


def get_all_classes(test_module_path):
    module_name = test_module_path.split('/')[-1].replace('.py','')
    package_path = os.path.dirname(test_module_path)
    return pyclbr.readmodule(module_name, path=[package_path])


def get_super_class_names(class_to_inspect):
    try:
        class_to_inspect_definition = all_classes_by_names[class_to_inspect]
    except KeyError:
        # Probably a class from non-test-code
        return []
    return map(
        lambda cur_super_cls: cur_super_cls if type(cur_super_cls) is str else cur_super_cls.name,
        class_to_inspect_definition.super
    )


def does_class_inherit_from_certain_superclass(class_to_inspect, superclass_to_look_for):
    super_classes = get_super_class_names(class_to_inspect)
    if not super_classes:
        return False
    if super_classes == ['object']:
        return False
    if superclass_to_look_for in super_classes:
        return True
    else:
        return any([
            does_class_inherit_from_certain_superclass(cur_super_class, superclass_to_look_for)
            for cur_super_class in super_classes
        ])


def class_or_superclasses_have_test_methods(class_to_inspect):
    super_classes = get_super_class_names(class_to_inspect)
    if not super_classes:
        return False

    class_to_inspect_definition = all_classes_by_names[class_to_inspect]
    if class_to_inspect_definition.methods:
        do_test_methods_exist = any(map(
            lambda method_name: method_name.startswith('test_'),
            class_to_inspect_definition.methods.keys()
        ))
        if do_test_methods_exist:
            return True
    return any([
        class_or_superclasses_have_test_methods(cur_super_class)
        for cur_super_class in super_classes
    ])


def get_super_classes_without_test_methods(class_to_inspect, super_class_names_to_ignore=None):
    super_classes = get_super_class_names(class_to_inspect)
    super_classes = set(super_classes)
    super_classes.discard('object')
    if super_class_names_to_ignore:
        super_classes = super_classes.difference(set(super_class_names_to_ignore))
    return super_classes.difference(test_case_names_by_method_def)  # Better check for all_test_case_names ?


def get_class_reference(class_name, project_path, cut_off=None):
    class_details = all_classes_by_names[class_name]
    class_reference = class_details.file.rstrip('.py').lstrip(project_path).replace('/', '.') + '.' + class_name
    if cut_off:
        class_reference = class_reference.lstrip(cut_off + '.')
    return class_reference


def is_test_case_passing(class_reference, shell_test_cmd, project_path):
    whole_command = ["cd", project_path, "&&", shell_test_cmd.format(class_reference)]
    command = ' '.join(whole_command)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    print proc_stdout
    return not bool(process.returncode)


def is_class_a_test_case_by_its_methods(class_name):
    return class_name in test_case_names_by_method_def


def is_class_within_project(class_name, project_path):
    class_details = all_classes_by_names[class_name]
    return project_path in class_details.file


def remove_superclass_within_file(class_name, superclass_to_be_removed):
    class_details = all_classes_by_names[class_name]
    with open(class_details.file, 'r+') as source_file:
        file_content = source_file.read()

        def repl_from_cls_list(matchobj):
            class_header = matchobj.group(0)
            ordered_token_removal_list = [
                superclass_to_be_removed + ',',
                ',' + superclass_to_be_removed,
                superclass_to_be_removed
            ]
            for token_to_remove in ordered_token_removal_list:
                if token_to_remove in class_header:
                    return class_header.replace(token_to_remove, '')
            raise Exception('Removing failed.')

        if not re.search(SUPER_CLASSES_RE.format(class_name=class_name), file_content, re.MULTILINE).group(0):
            raise Exception(class_name + ' could not be found in the file.')
        elif not superclass_to_be_removed in \
            re.search(SUPER_CLASSES_RE.format(class_name=class_name), file_content, re.MULTILINE).group('super'):
            raise Exception(superclass_to_be_removed + ' superclass could not be found in class header.')

        new_content = re.sub(
            SUPER_CLASSES_RE.format(class_name=class_name),
            repl_from_cls_list,
            string=file_content,
            count=1,
            flags=re.MULTILINE
        )
        source_file.seek(0)
        source_file.truncate()
        source_file.write(new_content)


class GitHelper(object):
    def __init__(self, project_path):
        self.project_path = project_path
        self.bare_repo = Repo.init(project_path, bare=True)
        # self.cli = Git(working_dir=project_path)  #os.path.expanduser("~/git/GitPython")
        # print self.cli.execute(['git', 'symbolic-ref --short HEAD'])

        if self.are_files_modified():
            raise Exception('There are modified files, please commit them before I start again.')
        self.start_working_branch()
        # if self.bare_repo.active_branch.name == 'master':
        #     raise Exception('I won\'t do anything on your master branch!!!')

    def are_files_modified(self):
        return bool(len(self.bare_repo.index.diff(None)))

    def revert_changes(self):
        file_paths = map(lambda o: o.a_path, self.bare_repo.index.diff(None))
        self.bare_repo.index.checkout(file_paths, force=True)

    def commit_and_push_changes(self, message):
        self.bare_repo.git.add(update=True)
        self.bare_repo.git.commit(message=message)
        # self.bare_repo.git.push()

    def start_working_branch(self):
        self.bare_repo.git.checkout('gravedigger')


if __name__ == '__main__':
    PROJECT_PATH = sys.argv[1]
    CLASS_REFERENCE_CUTOFF = sys.argv[2]
    TEST_CASE_INDICATOR_CLASS_NAMES = sys.argv[3].split(',')
    test_modules = find_test_modules(root_path=PROJECT_PATH)
    git_helper = GitHelper(project_path=PROJECT_PATH)

    ###################################
    print '* Collect all possible test classes...'
    for cur_test_module in test_modules:
        cur_classes_by_names = get_all_classes(cur_test_module)
        all_classes_by_names.update(cur_classes_by_names)  # Expecting class names to be unique across project!

    ###################################
    print '* Analyze all test classes...'
    for class_name, class_details in all_classes_by_names.items():
        if does_class_inherit_from_certain_superclass(class_name, TEST_CASE_INDICATOR_CLASS_NAMES[0]) or \
           does_class_inherit_from_certain_superclass(class_name, TEST_CASE_INDICATOR_CLASS_NAMES[1]):
            test_case_names_by_inheritance.add(class_name)

        if class_or_superclasses_have_test_methods(class_name):
            test_case_names_by_method_def.add(class_name)

    all_test_case_names = test_case_names_by_inheritance.intersection(test_case_names_by_method_def)

    print '* Refactor obsolete inherited super classes of all test cases...'
    for cur_test_case_name in all_test_case_names:
        superclasses_without_test_methods = get_super_classes_without_test_methods(
            cur_test_case_name,
            super_class_names_to_ignore=TEST_CASE_INDICATOR_CLASS_NAMES
        )

        for superclass_to_be_removed in superclasses_without_test_methods:
            if git_helper.are_files_modified():
                raise Exception('Some changes couldn\'t be commited!')
            if is_class_within_project(cur_test_case_name, PROJECT_PATH):
                remove_superclass_within_file(cur_test_case_name, superclass_to_be_removed)
            else:
                continue

            cur_class_reference = get_class_reference(cur_test_case_name, PROJECT_PATH, cut_off=CLASS_REFERENCE_CUTOFF)

            print '* Running test case: ' + cur_class_reference
            cur_class_successfully_refactored = is_test_case_passing(
                cur_class_reference,
                'make docker-test args="{} --failfast"',
                PROJECT_PATH
            )
            if cur_class_successfully_refactored:
                print 'SUCCESS'
                print '* Commiting changes...'
                git_helper.commit_and_push_changes("Simplified " + cur_test_case_name)
            else:
                print 'FAIL'
                print '* Reverting changes...'
                git_helper.revert_changes()

    ####################################
    # report
    print 'found total amt classes:'
    print len(all_classes_by_names.keys())

    print 'found test_case_names_by_inheritance:'
    print len(test_case_names_by_inheritance)

    print 'found test_case_names_by_method_def:'
    print len(test_case_names_by_method_def)

