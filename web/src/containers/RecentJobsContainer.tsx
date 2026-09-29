import { RecentJobs } from "../components/job/RecentJobs";
import { useRecentJobs } from "../hooks/useRecentJobs";

export function RecentJobsContainer({ onOpen }: { onOpen: (id: string) => void }) {
  const jobs = useRecentJobs();
  return <RecentJobs jobs={jobs} onOpen={onOpen} />;
}
