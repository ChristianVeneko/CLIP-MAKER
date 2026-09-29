import { useCallback, useEffect, useState } from "react";

/** Tiny hash router: "#/job/<id>" shows a job, anything else is the create view. */
export type Route = { name: "create" } | { name: "job"; id: string };

export function parseHash(hash: string): Route {
  const m = /^#\/job\/([a-f0-9]{12})$/.exec(hash);
  return m ? { name: "job", id: m[1] } : { name: "create" };
}

export function useHashRoute(): [Route, (r: Route) => void] {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const navigate = useCallback((r: Route) => {
    window.location.hash = r.name === "job" ? `#/job/${r.id}` : "#/";
  }, []);
  return [route, navigate];
}
