import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, MessageSquare, Phone } from "lucide-react";
import Shell from "../components/Shell.jsx";

export default function ChooseChannel() {
  const navigate = useNavigate();

  useEffect(() => {
    if (!localStorage.getItem("userId")) {
      navigate("/");
    }
  }, [navigate]);

  return (
    <Shell step={2}>
      <div className="step-label">Étape 2 / 4</div>
      <h2>Vérification en 2 étapes</h2>
      <p>Choisissez comment recevoir votre code</p>
      <div className="channel-list">
        <button className="channel-btn voice" onClick={() => navigate("/otp-call")}>
          <span className="channel-ico">
            <Phone size={20} />
          </span>
          <span className="channel-copy">
            <strong>Appel vocal</strong>
            <span>Le code est dicté au téléphone</span>
          </span>
        </button>
        <button className="channel-btn sms" onClick={() => navigate("/otp-sms")}>
          <span className="channel-ico">
            <MessageSquare size={20} />
          </span>
          <span className="channel-copy">
            <strong>SMS</strong>
            <span>Le code arrive sur votre téléphone</span>
          </span>
        </button>
        <button className="channel-btn email" onClick={() => navigate("/otp-email")}>
          <span className="channel-ico">
            <Mail size={20} />
          </span>
          <span className="channel-copy">
            <strong>E-mail</strong>
            <span>Le code arrive dans votre boîte</span>
          </span>
        </button>
      </div>
    </Shell>
  );
}
