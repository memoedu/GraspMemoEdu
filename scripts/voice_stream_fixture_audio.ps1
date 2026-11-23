param([Parameter(Mandatory)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($root) | Out-Null
Add-Type -AssemblyName System.Speech
$voice = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $zh = [Globalization.CultureInfo]::GetCultureInfo('zh-CN')
    $selected = $voice.GetInstalledVoices($zh) | Where-Object Enabled | Select-Object -First 1
    if (!$selected) { throw 'The synthetic acceptance recordings require a Windows Mandarin voice.' }
    $voice.SelectVoice($selected.VoiceInfo.Name)
    $voice.Rate = -1
    $format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000, 16, 1)
    $phrases = @{variable='艾克斯加三减歪'; coordinate='负一，一'; script='歪六';
                 integral='积分，艾克斯的平方加三乘艾克斯，微分艾克斯'; order='七减三乘二'}
    foreach ($sample in $phrases.GetEnumerator()) {
        $file = Join-Path $root ($sample.Key + '.wav')
        if (Test-Path -LiteralPath $file) { throw "Fixture output already exists: $file" }
        $voice.SetOutputToWaveFile($file, $format)
        $voice.Speak($sample.Value)
        $voice.SetOutputToNull()
    }
} finally { $voice.Dispose() }
