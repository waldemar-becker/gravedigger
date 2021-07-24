# Gravedigger - The dead code remover for python projects
This project is still in experimental mode and was written quick+dirty.

## Installation
Package for this project is not here yet.
### Unix
```
git clone https://github.com/waldemar-becker/gravedigger.git
cd gravedigger
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage
### Unix
```shell
source venv/bin/activate
# Remove all dead code findings from the vulture lib: 
python main.py project/to/manipulate
# Remove all dead code findings from obsolete test case inheritances: 
python remove_obsolete_test_inheritance.py project/to/manipulate class.reference.cutoff IndicatorClass1,IndicatorClass2
echo $?
```
Hints:
* `project/to/manipulate` analyze dead code in this python project and remove it in a separate git branch called `gravedigger`
* `class.reference.cutoff` references to modules which you use in class inheritances but might confuse gravedigger, therefore you can ignore them
* `IndicatorClass1,IndicatorClass2` tells gravedigger explicitly which classes shall be treated as test case classes

### Win
```shell
workon gravedigger
python main.py C:\project\to\manipulate\
echo $LastExitCode # powershell
```
