export function NoKeyBanner() {
  return (
    <div className="banner" role="status">
      <span aria-hidden>⚠</span>
      <div>
        <strong>Falta OPENAI_API_KEY.</strong> La selección automática de momentos necesita la clave. Sin ella solo puedes
        generar clips escribiendo rangos explícitos (por ejemplo <code>10:30-11:15</code>) en “Momentos específicos”.
      </div>
    </div>
  );
}
