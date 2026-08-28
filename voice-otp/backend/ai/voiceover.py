from pathlib import Path
import hashlib
import subprocess
import tempfile


CACHE_DIR = Path(__file__).resolve().parent.parent / "tmp" / "guide_audio"


def synthesize_french(text, dest=None):
    """Windows SAPI WAV for browser playback (keeps native sample rate)."""
    spoken = (text or "").strip()
    if not spoken:
        raise ValueError("empty_script")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(spoken.encode("utf-8")).hexdigest()[:20]
    dest = Path(dest) if dest else CACHE_DIR / f"{digest}.wav"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(spoken)
        txt_path = Path(handle.name)

    ps = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$chosen = $false
foreach ($voice in $synth.GetInstalledVoices()) {{
  $info = $voice.VoiceInfo
  if ($info.Culture.Name -like 'fr*') {{
    $synth.SelectVoice($info.Name)
    $chosen = $true
    break
  }}
}}
if (-not $chosen) {{
  try {{
    $synth.SelectVoiceByHints(
      [System.Speech.Synthesis.VoiceGender]::Female,
      [System.Speech.Synthesis.VoiceAge]::Adult,
      0,
      [System.Globalization.CultureInfo]::GetCultureInfo('fr-FR')
    )
  }} catch {{}}
}}
$synth.Rate = -1
$synth.Volume = 100
$synth.SetOutputToWaveFile('{dest.as_posix()}')
$synth.Speak([IO.File]::ReadAllText('{txt_path.as_posix()}', [Text.Encoding]::UTF8))
$synth.Dispose()
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0 or not dest.exists() or dest.stat().st_size < 1000:
            raise RuntimeError((result.stderr or result.stdout or "tts_failed")[:400])
    finally:
        txt_path.unlink(missing_ok=True)
    return dest
