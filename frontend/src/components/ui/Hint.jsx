import './ui.css';

export default function Hint({ children }) {
  if (!children) {
    return null;
  }
  return <p className="field__hint">{children}</p>;
}
