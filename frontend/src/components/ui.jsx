import './ui.css';

export function Card({ children, className = '', ...rest }) {
  return <div className={`ui-card ${className}`} {...rest}>{children}</div>;
}

export function Button({ variant = 'primary', size = 'md', className = '', ...rest }) {
  return <button className={`ui-btn ui-btn--${variant} ui-btn--${size} ${className}`} {...rest} />;
}

export function Field({ label, htmlFor, error, hint, children }) {
  return (
    <div className="ui-field">
      {label && <label htmlFor={htmlFor}>{label}</label>}
      {children}
      {hint && !error && <p className="ui-field__hint">{hint}</p>}
      {error && <p className="ui-field__error" role="alert">{error}</p>}
    </div>
  );
}

export function Input(props) {
  return <input className="ui-input" {...props} />;
}

export function Select({ children, ...props }) {
  return <select className="ui-input" {...props}>{children}</select>;
}

// A single radio option — compose a few of these under one `name` for a radio group.
export function Radio({ label, hint, ...props }) {
  return (
    <label className="ui-radio">
      <input type="radio" {...props} />
      <span className="ui-radio__box" aria-hidden="true" />
      <span className="ui-radio__text">
        <span className="ui-radio__label">{label}</span>
        {hint && <span className="ui-radio__hint">{hint}</span>}
      </span>
    </label>
  );
}

export function Banner({ tone = 'info', children }) {
  return <div className={`ui-banner ui-banner--${tone}`} role="status">{children}</div>;
}

export function EmptyState({ icon, title, message, action }) {
  return (
    <div className="ui-empty">
      {icon}
      <h3>{title}</h3>
      <p>{message}</p>
      {action}
    </div>
  );
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="ui-spinner-wrap" role="status" aria-live="polite">
      <div className="ui-spinner" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
