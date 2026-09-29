import { api } from "../api/client";
import { RecentJobs } from "../components/job/RecentJobs";
import { useRecentJobs } from "../hooks/useRecentJobs";

export function RecentJobsContainer({ onOpen }: { onOpen: (id: string) => void }) {
  const { jobs, reload } = useRecentJobs();
  const retry = async (id: string) => {
    try {
      await api.retryJob(id);
    } catch {
      /* the job stays failed; opening it shows the error */
    }
    reload();
  };
  return <RecentJobs jobs={jobs} onOpen={onOpen} onRetry={retry} />;
}
