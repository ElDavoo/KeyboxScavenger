# usage: . $0
lock_id=pif
set +o sh 2>/dev/null || :
exec 5<>"$TMPDIR/${lock_id}.lock" || exit 13
flock -n 0 <&5 || exit 13
echo $$ >&5
