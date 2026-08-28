import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, CircleAlert, UserRound } from "lucide-react";
import Shell from "../components/Shell.jsx";

export default function Login() {
  const navigate = useNavigate();
  const [userId, setUserId] = useState(
    () => localStorage.getItem("userId") || ""
  );
  const [error, setError] = useState("");

  function login() {
    const id = userId.trim();
    if (!id) {
      setError("Entrez votre identifiant.");
      return;
    }
    localStorage.setItem("userId", id);
    navigate("/choose-channel");
  }

  return (
    <Shell step={1}>
      <div className="step-label">Étape 1 / 4</div>
      <h2>Connexion</h2>
      <p className="hint">Identifiez-vous, puis choisissez comment recevoir le code.</p>
      <div className="field">
        <UserRound size={18} />
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="Identifiant"
          onKeyDown={(e) => e.key === "Enter" && login()}
        />
      </div>
      <button onClick={login}>
        Continuer
        <ArrowRight size={18} />
      </button>
      {error ? (
        <div className="error-msg">
          <CircleAlert size={16} />
          {error}
        </div>
      ) : null}
      <span className="link" onClick={() => navigate("/")}>
        Retour à l'accueil
      </span>
    </Shell>
  );
}
