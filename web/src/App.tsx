import { Header } from "./components/Header";
import { JobContainer } from "./containers/JobContainer";
import { CreateJobContainer } from "./containers/CreateJobContainer";
import { useConfig } from "./hooks/useConfig";
import { useHashRoute } from "./hooks/useHashRoute";

export function App() {
  const { config, error } = useConfig();
  const [route, navigate] = useHashRoute();
  return (
    <>
      <Header onHome={() => navigate({ name: "create" })} />
      {error && (
        <p className="error-text container" role="alert">
          No se pudo cargar la configuración: {error}
        </p>
      )}
      {config && route.name === "create" && (
        <CreateJobContainer config={config} onJobCreated={(id) => navigate({ name: "job", id })} />
      )}
      {config && route.name === "job" && <JobContainer id={route.id} onBack={() => navigate({ name: "create" })} />}
      <footer className="page-footer container">ClipMaker · procesamiento local</footer>
    </>
  );
}
