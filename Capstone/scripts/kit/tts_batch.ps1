param([string]$Manifest)
# Reads a JSON list of {out, text, voice, rate, pitch} and writes one WAV per item with the Windows speech engine.
Add-Type -AssemblyName System.Speech
$items = Get-Content -Raw -Encoding UTF8 $Manifest | ConvertFrom-Json
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$n = 0
foreach ($it in $items) {
    $dir = Split-Path -Parent $it.out
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    $s.SelectVoice($it.voice)
    $s.Rate = [int]$it.rate
    $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
    $s.SetOutputToWaveFile($it.out, $fmt)
    $text = [System.Security.SecurityElement]::Escape($it.text)
    $pitch = [string]$it.pitch
    $ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><prosody pitch='$pitch'>$text</prosody></speak>"
    $s.SpeakSsml($ssml)
    $s.SetOutputToNull()
    $n++
}
"wrote $n files"
