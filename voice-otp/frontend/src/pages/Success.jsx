import { useNavigate } from "react-router-dom";
import { BadgeCheck, RotateCcw } from "lucide-react";
import Shell from "../components/Shell.jsx";

const LABELS = {
  voice: "appel vocal",
  sms: "SMS",
  email: "e-mail",
};

export default function Success() {
  const navigate = useNavigate();
  const channel = localStorage.getItem("lastChannel") || "voice";

  function restart() {
    localStorage.clear();
    navigate("/");
  }

  return (
    <Shell step={4}>
      <div className="step-label">Étape 4 / 4</div>
      <div className="icon-badge ok">
        <BadgeCheck size={32} />
      </div>
      <h2 style={{ textAlign: "center" }}>Authentification réussie</h2>
      <p style={{ textAlign: "center" }}>
        Identité vérifiée par {LABELS[channel] || channel} (OTP)
      </p>
      <button className="secondary" onClick={restart}>
        <RotateCcw size={16} />
        Recommencer
      </button>
    </Shell>
  );
}
