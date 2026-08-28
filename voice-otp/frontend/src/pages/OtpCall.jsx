import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CircleAlert, PhoneCall } from "lucide-react";
import Shell from "../components/Shell.jsx";

const API_BASE = "http://127.0.0.1:5000";

export default function OtpCall() {
  const navigate = useNavigate();
  const [failMsg, setFailMsg] = useState("");
  const started = useRef(false);
  const userId = localStorage.getItem("userId");

  async function requestOtp() {
    try {
      const res = await fetch(`${API_BASE}/auth/request-voice-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId,
          phoneNumber: localStorage.getItem("phone") || "1000",
        }),
      });
      const data = await res.json();
      if (res.ok && data.status === "sent") {
        localStorage.setItem("lastChannel", "voice");
        localStorage.setItem("otpDest", "");
        navigate("/otp-enter");
      } else {
        setFailMsg(data.detail || "Échec de l'envoi de l'appel.");
      }
    } catch {
      setFailMsg(
        "Impossible de contacter le serveur. Vérifiez que le backend Flask tourne."
      );
    }
  }

  useEffect(() => {
    if (!userId) {
      navigate("/");
      return;
    }
    if (started.current) return;
    started.current = true;
    requestOtp();
  }, [navigate, userId]);

  if (failMsg) {
    return (
      <Shell step={3}>
        <div className="step-label">Erreur</div>
        <div className="icon-badge warn">
          <CircleAlert size={28} />
        </div>
        <h2>Échec</h2>
        <p>{failMsg}</p>
        <button onClick={() => { started.current = false; setFailMsg(""); requestOtp(); }}>
          Réessayer
        </button>
        <button onClick={() => navigate("/choose-channel")}>Retour</button>
      </Shell>
    );
  }

  return (
    <Shell step={3}>
      <div className="step-label">Étape 3 / 4</div>
      <div className="icon-badge pulse">
        <PhoneCall size={28} />
      </div>
      <h2>Appel en cours...</h2>
      <div className="status-msg">Nous vous appelons...</div>
    </Shell>
  );
}
