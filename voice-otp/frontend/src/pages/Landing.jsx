import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  KeyRound,
  Mail,
  MessageSquare,
  Phone,
  ShieldCheck,
  Timer,
} from "lucide-react";

const CHANNELS = [
  {
    icon: Phone,
    title: "Appel vocal",
    text: "Le code est dicté à l'oreille, sans SMS ni e-mail.",
    klass: "voice",
  },
  {
    icon: MessageSquare,
    title: "SMS",
    text: "Le code arrive sur le numéro saisi, en quelques secondes.",
    klass: "sms",
  },
  {
    icon: Mail,
    title: "E-mail",
    text: "Le code est envoyé uniquement à l'adresse indiquée.",
    klass: "email",
  },
];

const STEPS = [
  { n: "01", title: "Identifiant", text: "Connectez-vous avec votre identifiant." },
  { n: "02", title: "Canal", text: "Choisissez voix, SMS ou e-mail." },
  { n: "03", title: "Code OTP", text: "Recevez un code à 6 chiffres, valable 3 minutes." },
  { n: "04", title: "Accès", text: "Saisissez le code. L'identité est confirmée." },
];

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="landing">
      <div className="app-bg">
        <div className="orb orb-a" />
        <div className="orb orb-b" />
      </div>

      <header className="land-nav">
        <div className="land-brand">
          <span className="brand-mark">
            <ShieldCheck size={20} />
          </span>
          Voice OTP
        </div>
        <button className="land-nav-cta" onClick={() => navigate("/login")}>
          Commencer
          <ArrowRight size={16} />
        </button>
      </header>

      <main className="land-main">
        <section className="land-hero">
          <p className="land-kicker">Vérification en deux étapes</p>
          <h1>
            Un code secret,
            <span> trois façons de le recevoir.</span>
          </h1>
          <p className="land-lead">
            Voice OTP protège l'accès à votre compte. Le code n'est jamais
            affiché à l'écran : il arrive par appel vocal, SMS ou e-mail,
            puis expire en 3 minutes.
          </p>
          <div className="land-actions">
            <button onClick={() => navigate("/login")}>
              Essayer maintenant
              <ArrowRight size={18} />
            </button>
            <a className="land-ghost" href="#fonctionnement">
              Comment ça marche
            </a>
          </div>

          <div className="hero-visual" aria-hidden="true">
            <div className="hero-ring" />
            <div className="hero-ring delay" />
            <div className="hero-phone">
              <KeyRound size={36} />
              <strong>OTP</strong>
              <span>• • • • • •</span>
            </div>
          </div>
        </section>

        <section className="land-section">
          <h2>Choisissez votre canal</h2>
          <p className="land-sub">
            Un seul code, trois canaux. Vous décidez comment le recevoir.
          </p>
          <div className="land-grid">
            {CHANNELS.map((item) => {
              const Icon = item.icon;
              return (
                <article key={item.title} className={`land-card ${item.klass}`}>
                  <div className="land-ico">
                    <Icon size={22} />
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="land-section" id="fonctionnement">
          <h2>Comment ça fonctionne</h2>
          <p className="land-sub">Quatre étapes simples, de la connexion à l'accès.</p>
          <ol className="land-steps">
            {STEPS.map((step) => (
              <li key={step.n}>
                <span>{step.n}</span>
                <div>
                  <strong>{step.title}</strong>
                  <p>{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="land-section">
          <h2>Sécurité intégrée</h2>
          <p className="land-sub">
            Le code n'est pas stocké en clair. Les abus sont bloqués.
          </p>
          <div className="land-grid security">
            <article className="land-card">
              <div className="land-ico">
                <Timer size={22} />
              </div>
              <h3>Expire en 3 min</h3>
              <p>Après 180 secondes, le code n'est plus valable.</p>
            </article>
            <article className="land-card">
              <div className="land-ico">
                <ShieldCheck size={22} />
              </div>
              <h3>3 tentatives max</h3>
              <p>Trop d'erreurs : le code est invalidé, il faut en demander un autre.</p>
            </article>
            <article className="land-card">
              <div className="land-ico">
                <BadgeCheck size={22} />
              </div>
              <h3>Limite par IP</h3>
              <p>3 demandes maximum toutes les 5 minutes, pour éviter le spam.</p>
            </article>
          </div>
        </section>

        <section className="land-cta-band">
          <h2>Prêt à vérifier votre identité ?</h2>
          <p>Lancez une authentification en quelques secondes.</p>
          <button onClick={() => navigate("/login")}>
            Démarrer la vérification
            <ArrowRight size={18} />
          </button>
        </section>
      </main>
    </div>
  );
}
