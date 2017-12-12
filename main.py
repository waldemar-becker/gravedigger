"""
workon dead_code_remover
python main.py C:\projects\stdnum\
echo $LastExitCode # powershell
"""

from vulture.core import _parse_args, Vulture
from vulture import utils


class DeletionJob(object):
    def __init__(self, file_path, first_lineno, last_lineno, reason):
        self.file_path = file_path
        self.first_lineno = first_lineno
        self.last_lineno = last_lineno
        self.reason = reason

    def run(self):
        pass

    def __repr__(self):
        return str(self.__dict__)

		
if __name__ == '__main__':
    options, args = _parse_args()
    vulture = Vulture(verbose=options.verbose)
    vulture.scavenge(args, exclude=options.exclude)
    code_items = vulture.get_unused_code(
        min_confidence= 90,#options.min_confidence,
        sort_by_size=options.sort_by_size
    )

    DELETION_JOBS = []

    for item in code_items:
        DELETION_JOBS.append(DeletionJob(
            file_path=utils.format_path(item.filename),
            first_lineno=item.first_lineno,
            last_lineno=item.last_lineno,
            reason=item.message + ' ({}% confidence)'.format(item.confidence)
        ))

    print DELETION_JOBS
