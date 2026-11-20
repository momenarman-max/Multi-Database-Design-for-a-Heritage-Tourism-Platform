# Windows native runner for the portable services used on the author's machine.
# Point ATLAS_RUNTIME at the extracted tools and initialized data to relocate them.
$ErrorActionPreference = 'Stop'
$runtime = $env:ATLAS_RUNTIME
if (-not $runtime) { $runtime = Join-Path $PSScriptRoot '../../work' }
$runtime = (Resolve-Path $runtime).Path
$python = Join-Path $runtime 'venv/Scripts/python.exe'
if (-not (Test-Path $python)) { throw 'Portable runtime missing. Follow the Docker or native instructions in README.md.' }
function Listening([int]$port) {
    $socket = New-Object Net.Sockets.TcpClient
    try { $socket.Connect('127.0.0.1',$port); return $true } catch { return $false } finally { $socket.Dispose() }
}
if (-not (Listening 55432)) {
    $pg = (Resolve-Path "$runtime/postgresql-16.6-1-windows-x64-binaries.zip.dir/pgsql/bin/pg_ctl.exe").Path
    & $pg -D "$runtime/pgdata" -l "$runtime/pg.log" -o '-p 55432 -h 127.0.0.1' start
    if ($LASTEXITCODE) { throw 'PostgreSQL startup failed.' }
}
if (-not (Listening 57017)) {
    $mongo = (Resolve-Path "$runtime/mongodb-win32-x86_64-windows-7.0.28/bin/mongod.exe").Path
    Start-Process $mongo -WindowStyle Hidden -ArgumentList "--bind_ip 127.0.0.1 --port 57017 --dbpath `"$runtime/mdb`" --logpath `"$runtime/mdb.log`" --logappend"
}
if (-not (Listening 56379)) {
    $redis = (Resolve-Path "$runtime/Redis-x64-5.0.14.1.zip.dir/redis-server.exe").Path
    Start-Process $redis -WindowStyle Hidden -WorkingDirectory $runtime -ArgumentList '--bind 127.0.0.1 --port 56379 --save "" --appendonly no'
}
if (-not (Listening 57687)) {
    $neo = (Resolve-Path "$runtime/neo4j-community-5.26.0-windows.zip.dir/neo4j-community-5.26.0/bin/neo4j.bat").Path
    Start-Process $neo -WindowStyle Hidden -ArgumentList console
}
foreach ($port in @(55432,57017,57687,56379)) {
    $deadline = (Get-Date).AddSeconds(100)
    while (-not (Listening $port)) {
        if ((Get-Date) -gt $deadline) { throw "Service on port $port is unavailable; inspect $runtime." }
        Start-Sleep -Milliseconds 500
    }
}
$env:PGHOST='127.0.0.1'
$env:PGPORT='55432'
$env:PGDATABASE='postgres'
$env:PGUSER='atlas'
$env:GRAPH_URI='bolt://127.0.0.1:57687'
$env:GRAPH_PASSWORD=''
$env:MONGO_URI='mongodb://127.0.0.1:57017'
$env:REDIS_URL='redis://127.0.0.1:56379'
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
if ($args.Count -and $args[0] -eq 'test') { & $python "$PSScriptRoot/project/tests/integration.py" }
else { & $python "$PSScriptRoot/project/app/atlas.py" @args }
exit $LASTEXITCODE
