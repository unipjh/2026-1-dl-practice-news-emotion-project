import EmotionBarChart from "./EmotionBarChart";
import HeadlineList from "./HeadlineList";
import TimeseriesModal from "./TimeseriesModal";

export default function MonitoringView() {
  return (
    <main className="max-w-[1280px] mx-auto px-6 py-6">
      <EmotionBarChart />
      <HeadlineList />
      <TimeseriesModal />
    </main>
  );
}
