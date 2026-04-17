# usage: . $0
lock_id=pif
(pid=
exec 2>/dev/null
set +euo sh || :
if ! flock -n 0; then
  read pid
  kill $pid >/dev/null
  timeout 10 flock 0
  kill -KILL $pid >/dev/null
  flock 0
fi) <>"$TMPDIR/${lock_id}.lock" || :
