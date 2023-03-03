@echo off
cd ..

set PYGETTEXT=C:\Python310\Tools\i18n\pygettext.py
if defined PYGETTEXT_DIRECTORY (
    set PYGETTEXT=%PYGETTEXT_DIRECTORY%\pygettext.py
)

echo Regenerating translations .pot file
python %PYGETTEXT% -d find-duplicates -p translations^
 action.py config.py book_algorithms.py dialogs.py ..\common\common_*.py^
 duplicates.py advanced\*.py advanced\gui\*.py

set PYGETTEXT=
cd .build
