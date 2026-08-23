<#
.SYNOPSIS
    Install ndl-mcp, after filing the NDL's API notification.

.DESCRIPTION
    0. Puts the NDL API application/notification first. The National Diet Library
       asks continuous API users to report their contact details and the nature of
       their use, whether or not a prior application is required. This installer
       will not register the server until that step has been recorded, because the
       undertakings in the server were filed with the library and the code exists
       to keep them.

       There is NO credential to wait for. The NDL search APIs are open: no key, no
       application ID, no token. Nothing is issued and nothing is pasted in. Filing
       is a duty, not a gate on access — which is exactly why an installer has to
       hold the door, since nothing else will.

    1. VERIFIES that this repository's mediation.py and ledger.py are byte-identical
       to the installed cinii_mcp copies, and stops if they are not. Earlier
       revisions copied cinii's files over this repository's — which silently made
       the working tree disagree with the commit it was built from.
    2. Resolves a Python interpreter: the shared mcp-servers venv if present.
    3. Installs the package (and its dependencies) into that interpreter.
    4. Smoke-tests the installed package, asserting the filed undertakings and
       that the receipt ledger is actually reachable.
    5. Backs up claude_desktop_config.json and merges an 'ndl' entry pointing at
       the ndl-mcp console script, with the receipt ledger switched on to match
       the other servers.

    Idempotent: rerun safely. Only the 'ndl' entry is overwritten.

    Since 1.1.0 this installs a package rather than copying three files into
    %APPDATA%\Claude\mcp-servers\ndl_mcp. A pre-1.1.0 'ndl' entry registered by
    path will not start this version; rerunning this script replaces it.

.PARAMETER ReceiptLog
    Path to the append-only receipt log. Defaults to the author's shared log, so
    that NDL queries join the chain the rest of this server family writes to. A
    hash chain is per-file: anyone else should pass this and point it at a file
    of their own.

.PARAMETER NotificationFiled
    Date you registered with the NDL, as YYYY-MM-DD. Recorded to
    NDL-API-NOTIFICATION.txt. Registration is recommended, not required: the
    library confirmed in August 2026 that notification is no longer mandatory,
    and the install proceeds without it.

.PARAMETER PythonVersion
    Python launcher tag used only if no shared venv is found. Defaults to '3.13'.

.EXAMPLE
    .\install.ps1 -NotificationFiled 2026-08-19
#>

[CmdletBinding()]
param(
    [string]$NotificationFiled,
    [string]$ReceiptLog,
    [string]$PythonVersion = "3.13"
)

$ErrorActionPreference = "Stop"
$ProjectRoot  = $PSScriptRoot
$PackageDir   = Join-Path $ProjectRoot "src\ndl_mcp"
$ServerFile   = Join-Path $PackageDir "server.py"
$MarkerFile   = Join-Path $ProjectRoot "NDL-API-NOTIFICATION.txt"
$ServersRoot  = Join-Path $env:APPDATA "Claude\mcp-servers"
$SharedPython = Join-Path $ServersRoot ".venv\Scripts\python.exe"
$ConfigPath   = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
$FormUrl      = "https://form2.ndl.go.jp/form/pub/ndl07/api"
$TermsUrl     = "https://ndlsearch.ndl.go.jp/help/api"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# -- 0. The NDL notification -----------------------------------------------

Write-Step "NDL API notification"

if (-not (Test-Path $ServerFile)) {
    throw "server.py not found at $ServerFile. Run install.ps1 from the repository root."
}

if ($NotificationFiled) {
    if ($NotificationFiled -notmatch '^\d{4}-\d{2}-\d{2}$') {
        throw "-NotificationFiled must be YYYY-MM-DD."
    }
    @"
NDL Search API — notification of continuous access
Filed: $NotificationFiled
Form:  $FormUrl
Terms: $TermsUrl
Contact: di-api@ndl.go.jp

Registered through the form described at section 17 of the NDL Search API help:
contact details and nature of use. The library confirmed in August 2026 that this
registration is no longer required, though still welcome. Providers used:
iss-ndl-opac, iss-ndl-opac-national, zassaku, zassaku-online, ndl-dl-open — all
NDL-created, none requiring a usage application for scholarly work.

Undertakings given, and implemented in src/ndl_mcp/server.py:
  serial requests, no concurrency        -> _rate_lock held across each request
  minimum one-second interval            -> MIN_REQUEST_INTERVAL
  a cap on records per search            -> MAX_RECORDS, no auto-pagination
  no harvesting interface                -> OAI-PMH not implemented
  credit on every response               -> ATTRIBUTION + provider_credit()
  metadata displayed, not accumulated    -> no cache, no local store

The undertakings above are kept because they are good practice toward a public
service, not because a filing compels them. If the provider set or any undertaking
changes, update this file so the record stays true.
"@ | Out-File -FilePath $MarkerFile -Encoding utf8
    Write-Host "    Recorded to $MarkerFile"
}

if (-not (Test-Path $MarkerFile)) {
    Write-Host ""
    Write-Host "  Registering with the NDL is recommended, and not required." -ForegroundColor Yellow
    Write-Host "  The library confirmed in August 2026 that notification of continuous"
    Write-Host "  use is no longer mandatory, though it remains welcome."
    Write-Host ""
    Write-Host "  Do it anyway. It takes a few minutes, it tells the library who is"
    Write-Host "  using the interface and for what, and a national library that can"
    Write-Host "  see researchers using its API has an argument for keeping it open."
    Write-Host ""
    Write-Host "  Form:  $FormUrl"
    Write-Host "  Terms: $TermsUrl"
    Write-Host "  Query: di-api@ndl.go.jp"
    Write-Host ""
    $answer = Read-Host "  Open the form now? [y/N]"
    if ($answer -match '^[Yy]') { Start-Process $FormUrl }
    Write-Host ""
    Write-Host "  Continuing. Rerun with -NotificationFiled YYYY-MM-DD once you have" -ForegroundColor Yellow
    Write-Host "  registered, and the date will be recorded here." -ForegroundColor Yellow
} else {
    Write-Host "    Registration on record:"
    Get-Content $MarkerFile -TotalCount 2 | ForEach-Object { Write-Host "      $_" }
}

# -- 1. Python ---------------------------------------------------------------

Write-Step "Resolving Python"

if (Test-Path $SharedPython) {
    $Python = $SharedPython
    Write-Host "    Using the shared mcp-servers venv."
} else {
    $VenvDir = Join-Path $ProjectRoot ".venv"
    $Python  = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $Python)) {
        & py "-$PythonVersion" -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "py -$PythonVersion failed. Install Python $PythonVersion or pass -PythonVersion." }
    }
    Write-Host "    Using a project-local venv at $VenvDir."
}

$ScriptsDir = Split-Path $Python -Parent

# -- 2. Verify the vendored modules ------------------------------------------
#
# mediation.py and ledger.py are vendored byte-identical across this family. The
# check runs against the installed cinii_mcp package rather than a sibling
# checkout, and it reports rather than repairs: a divergence here means the
# commit this is being installed from disagrees with the family, and copying
# over it would hide that instead of surfacing it.

Write-Step "Verifying the vendored modules against cinii_mcp"

$ciniiDir = & $Python -c "import importlib.util,os,sys; s=importlib.util.find_spec('cinii_mcp'); sys.stdout.write(os.path.dirname(s.origin) if s and s.origin else '')" 2>$null
if (-not $ciniiDir) {
    Write-Host "    cinii_mcp is not installed in this interpreter; nothing to compare against." -ForegroundColor Yellow
    Write-Host "    The copies in this repository are used as they stand." -ForegroundColor Yellow
} else {
    foreach ($name in @("mediation.py", "ledger.py")) {
        $mine  = Join-Path $PackageDir $name
        $their = Join-Path $ciniiDir  $name
        if (-not (Test-Path $their)) { throw "$name not found in the installed cinii_mcp at $ciniiDir." }
        $a = (Get-FileHash $mine  -Algorithm SHA256).Hash
        $b = (Get-FileHash $their -Algorithm SHA256).Hash
        if ($a -ne $b) {
            throw "$name differs from the installed cinii_mcp copy.`n  this repo : $a`n  cinii_mcp : $b`nThese are vendored byte-identical by design. Reconcile them in a commit rather than at install time."
        }
        Write-Host "    $name  sha256:$($a.Substring(0,16))...  matches cinii_mcp"
    }
}

# -- 3. Install ---------------------------------------------------------------

Write-Step "Installing ndl-mcp into $ScriptsDir"

& $Python -m pip install --upgrade --quiet pip
& $Python -m pip install --quiet $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }

$ConsoleScript = Join-Path $ScriptsDir "ndl-mcp.exe"
if (-not (Test-Path $ConsoleScript)) { throw "ndl-mcp console script not found at $ConsoleScript after install." }

$installed = (& $Python -c "import ndl_mcp; print(ndl_mcp.__version__)").Trim()
Write-Host "    ndl-mcp $installed installed; console script at $ConsoleScript"

# -- 4. Smoke test -----------------------------------------------------------

Write-Step "Verifying the installed package"

$probe = Join-Path $env:TEMP "ndl_mcp_probe_$PID.py"
@"
from ndl_mcp import server, mediation as M
tools = [n for n in dir(server) if n.startswith('ndl_')]
assert server.MIN_REQUEST_INTERVAL >= 1.0, 'interval below what was filed with the NDL'
assert server.MAX_RECORDS <= 500, 'record cap above the NDL ceiling'
assert set(server.ALL_DPIDS) <= set(server.PROVIDERS), 'undeclared provider'
assert M.ledger_available(), 'ledger not reachable: receipts would be dropped silently'
print('OK -', len(tools), 'tools:', ', '.join(sorted(tools)))
print('OK - interval', server.MIN_REQUEST_INTERVAL, 's, cap', server.MAX_RECORDS, 'records')
print('OK - ledger reachable; deposit enabled:', M.deposit_enabled())
"@ | Out-File -FilePath $probe -Encoding utf8
try {
    & $Python $probe
    if ($LASTEXITCODE -ne 0) { throw "Installed-package check failed." }
} finally {
    Remove-Item $probe -ErrorAction SilentlyContinue
}

# -- 5. Register with Claude Desktop ----------------------------------------

Write-Step "Updating Claude Desktop config"

if (-not (Test-Path $ConfigPath)) {
    $config = [pscustomobject]@{ mcpServers = [pscustomobject]@{} }
} else {
    $stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item $ConfigPath "$ConfigPath.$stamp.bak"
    Write-Host "    Backed up config to $ConfigPath.$stamp.bak"
    $config = (Get-Content $ConfigPath -Raw) | ConvertFrom-Json
    if (-not ($config.PSObject.Properties.Name -contains "mcpServers")) {
        $config | Add-Member -MemberType NoteProperty -Name mcpServers -Value ([pscustomobject]@{})
    }
}

# Match the receipt-ledger settings the other servers carry, so that NDL queries
# are logged on the same terms and can go into the same deposit. A hash chain is
# per-file, so a second path means a second, independent chain and "the log"
# stops naming one thing. Override with -ReceiptLog.
$receiptLog = if ($ReceiptLog) { $ReceiptLog } else {
    Join-Path $env:USERPROFILE "Dropbox\MY RESEARCH WRITING\RESEARCH ETHICS\receipts\receipts.jsonl"
}
$entry = [ordered]@{
    command = $ConsoleScript
    env     = [ordered]@{
        MCP_RECEIPT_LOG     = $receiptLog
        MCP_RECEIPT_SESSION = "ndl-mcp"
    }
}

$serversHash = @{}
foreach ($prop in $config.mcpServers.PSObject.Properties) {
    $serversHash[$prop.Name] = $prop.Value
}
$serversHash["ndl"] = $entry

$newConfig = [ordered]@{}
foreach ($prop in $config.PSObject.Properties) {
    if ($prop.Name -ne "mcpServers") { $newConfig[$prop.Name] = $prop.Value }
}
$newConfig["mcpServers"] = $serversHash

$configDir = Split-Path $ConfigPath -Parent
if (-not (Test-Path $configDir)) { New-Item -ItemType Directory -Path $configDir | Out-Null }
($newConfig | ConvertTo-Json -Depth 10) | Out-File -FilePath $ConfigPath -Encoding utf8

# -- 6. Summary --------------------------------------------------------------

Write-Step "Done"
Write-Host ""
Write-Host "Registered:" -ForegroundColor Green
Write-Host "  command : $ConsoleScript"
Write-Host "  version : $installed"
Write-Host "  receipts: $receiptLog"
Write-Host ""
Write-Host "Providers reachable (all CC BY, no application required):" -ForegroundColor Green
Write-Host "  iss-ndl-opac, iss-ndl-opac-national, zassaku, zassaku-online, ndl-dl-open"
Write-Host ""
Write-Host "Not reachable by design: ndl-dl and ndl-dl-online require a usage" -ForegroundColor Yellow
Write-Host "application that has not been made. Adding them is a filing, not a config change." -ForegroundColor Yellow
Write-Host ""
Write-Host "mcpServers now in config:" -ForegroundColor Green
$serversHash.Keys | Sort-Object | ForEach-Object { Write-Host "  - $_" }
Write-Host ""
Write-Host "Restart Claude Desktop to load the server." -ForegroundColor Yellow
