echo
echo Running backup script, it is now `date`
echo ---------------------------------------
echo
cd `dirname $0`
export PYTHONPATH=boto
python backup.py
