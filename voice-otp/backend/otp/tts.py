import array
import subprocess
import wave
from pathlib import Path

SOUNDS_ROOT = Path(__file__).resolve().parents[2] / "asterisk-sounds"
DIGIT_DIR = SOUNDS_ROOT / "en" / "digits"
CUSTOM_DIR = SOUNDS_ROOT / "en"

DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


def _speak_to_wav(text: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".sapi.wav")
    # System.Speech is built into Windows; no extra packages needed.
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = -2; "
        f"$s.SetOutputToWaveFile('{tmp.as_posix()}'); "
        f"$s.Speak('{text}'); "
        "$s.Dispose();"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        check=True,
        capture_output=True,
        text=True,
    )
    _to_asterisk_wav(tmp, dest)
    tmp.unlink(missing_ok=True)


def _to_asterisk_wav(src: Path, dest: Path) -> None:
    with wave.open(str(src), "rb") as inf:
        nchannels = inf.getnchannels()
        sampwidth = inf.getsampwidth()
        framerate = inf.getframerate()
        frames = inf.readframes(inf.getnframes())

    if sampwidth != 2:
        raise RuntimeError(f"unsupported sample width: {sampwidth}")

    samples = array.array("h")
    samples.frombytes(frames)
    if nchannels == 2:
        samples = array.array(
            "h",
            ((samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples) - 1, 2)),
        )

    if framerate != 8000:
        ratio = framerate / 8000
        out = array.array("h")
        n = int(len(samples) / ratio)
        for i in range(max(n, 1)):
            out.append(samples[min(int(i * ratio), len(samples) - 1)])
        samples = out

    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as outf:
        outf.setnchannels(1)
        outf.setsampwidth(2)
        outf.setframerate(8000)
        outf.writeframes(samples.tobytes())


def generate_digit_sounds() -> None:
    DIGIT_DIR.mkdir(parents=True, exist_ok=True)
    for digit, word in DIGIT_WORDS.items():
        dest = DIGIT_DIR / f"{digit}.wav"
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        _speak_to_wav(word, dest)


def generate_otp_wav(otp_code: str) -> Path:
    spaced = " ".join(otp_code)
    text = f"Your verification code is {spaced}. I repeat: {spaced}."
    dest = CUSTOM_DIR / "otp.wav"
    _speak_to_wav(text, dest)
    return dest


def speak_locally(otp_code: str) -> None:
    """Play the OTP on the Windows PC speaker so local tests are audible even if SIP RTP fails."""
    spaced = " ".join(otp_code)
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = -2; "
        f"$s.Speak('Your verification code is {spaced}');"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", ps],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
