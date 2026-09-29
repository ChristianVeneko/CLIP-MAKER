import { Header } from "./components/Header";
import { CreateJobContainer } from "./containers/CreateJobContainer";
import { useConfig } from "./hooks/useConfig";
import { useHashRoute } from "./hooks/useHashRoute";

export function App() {
  const { config, error } = useConfig();
  const [, navigate] = useHashRoute();
  return (
    <>
      <Header onHome={() => navigate({ name: "create" })} />
      {error && (
        <p className="error-text container" role="alert">
          No se pudo cargar la configuración: {error}
        </p>
      )}
      {config && <CreateJobContainer config={config} />}
      <footer className="page-footer container">ClipMaker · procesamiento local</footer>
    </>
  );
}
