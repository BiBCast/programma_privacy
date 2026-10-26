# Prepara Tesseract in vendor/tesseract, senza installarlo e senza diritti di amministratore.
#
# Scarica l'installer ufficiale (build UB Mannheim pubblicata da tesseract-ocr), ne verifica
# l'impronta, ne estrae i file con 7-Zip e aggiunge il modello italiano, anch'esso verificato.
# Lo usano la CI e chi sviluppa; il pacchetto (M6) copierà la stessa cartella.
#
# Uso: powershell -ExecutionPolicy Bypass -File scripts/prepara_tesseract.ps1

$ErrorActionPreference = "Stop"

$versione = "5.5.3.20260724"
$installer_url = "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-$versione.exe"
$installer_sha256 = "bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4"
$modello_url = "https://github.com/tesseract-ocr/tessdata_best/raw/main/ita.traineddata"
$modello_sha256 = "8df9c89176fb93f56bf4b2d4ede04c01c1f31d4b7697fbd76cc336df700f3f38"

$radice = Split-Path -Parent $PSScriptRoot
$destinazione = Join-Path $radice "vendor\tesseract"
$temporanea = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [System.IO.Path]::GetTempPath() }
$installer = Join-Path $temporanea "tesseract-ocr-w64-setup-$versione.exe"

function Verifica($percorso, $atteso) {
    $impronta = (Get-FileHash $percorso -Algorithm SHA256).Hash.ToLower()
    if ($impronta -ne $atteso) { throw "Impronta diversa per ${percorso}: $impronta" }
}

$sette = (Get-Command 7z -ErrorAction SilentlyContinue).Source
if (-not $sette) { $sette = "C:\Program Files\7-Zip\7z.exe" }
if (-not (Test-Path $sette)) { throw "Serve 7-Zip per estrarre l'installer." }

Write-Host "Scarico Tesseract $versione"
Invoke-WebRequest -Uri $installer_url -OutFile $installer -UseBasicParsing
Verifica $installer $installer_sha256
& $sette x $installer "-o$destinazione" -y | Out-Null
Remove-Item $installer

Write-Host "Scarico il modello italiano"
$modello = Join-Path $destinazione "tessdata\ita.traineddata"
Invoke-WebRequest -Uri $modello_url -OutFile $modello -UseBasicParsing
Verifica $modello $modello_sha256

& (Join-Path $destinazione "tesseract.exe") --version | Select-Object -First 1
