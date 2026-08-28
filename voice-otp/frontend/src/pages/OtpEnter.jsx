import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CircleAlert, KeyRound, Mail, MessageSquare, Phone, RefreshCw, ShieldCheck } from "lucide-react";
import Shell from "../components/Shell.jsx";

const API_BASE = "http://127.0.0.1:5000";

const CHANNEL_ICON = {
  voice: Phone,
  sms: MessageSquare,
  email: Mail,
};

export default function OtpEnter() {
  const navigate = useNavigate();
  const userId = localStorage.getItem("userId");
  const channel = localStorage.getItem("lastChannel") || "voice";
  const sentTo = localStorage.getItem("otpDest") || "";
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const ChannelIcon = CHANNEL_ICON[channel] || KeyRound;

  useEffect(() => {
    if (!userId) navigate("/");
  }, [navigate, userId]);

  async function verifyOtp() {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, otp }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        navigate("/success");
        return;
      }
      setError("Code invalide ou expiré. Réessayez.");
    } catch {
      setError("Erreur de connexion au serveur.");
    }
  }

  function resend() {
    if (channel === "email") navigate("/otp-email");
    else if (channel === "sms") navigate("/otp-sms");
    else navigate("/otp-call");
  }

  const titles = {
    voice: "Entrez le code entendu",
    sms: "Entrez le code reçu par SMS",
    email: "Entrez le code reçu par e-mail",
  };

  return (
    <Shell step={3}>
      <div className="step-label">Étape 3 / 4</div>
      <div className="icon-badge">
        <ChannelIcon size={28} />
      </div>
      <h2>{titles[channel] || "Entrez le code"}</h2>
      {sentTo ? <p className="dest">{sentTo}</p> : null}
      {channel === "email" ? (
        <p className="hint">Ouvrez votre boîte e-mail. Vérifiez aussi les spams.</p>
      ) : null}
      {channel === "sms" ? (
        <p className="hint">Ouvrez vos SMS et saisissez le code reçu sur ce numéro.</p>
      ) : null}
      <input
        className="otp-input"
        maxLength={6}
        placeholder="------"
        value={otp}
        onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
      />
      <button onClick={verifyOtp} disabled={otp.length !== 6}>
        Valider le code
        <ShieldCheck size={18} />
      </button>
      {error ? (
        <div className="error-msg">
          <CircleAlert size={16} />
          {error}
        </div>
      ) : null}
      <span className="link" onClick={resend}>
        <RefreshCw size={14} />
        Renvoyer le code
      </span>
    </Shell>
  );
}
