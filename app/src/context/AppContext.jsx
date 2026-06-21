import { createContext, useContext, useState, useCallback } from "react";
import { buildCompareGroups } from "../lib/filterLogic";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [dt, setDt] = useState("1d");
  const [sentimentGroup, setSentimentGroup] = useState("all");

  const [filterDraft, setFilterDraft] = useState({ publishers: [], categories: [] });
  const [activeFilter, setActiveFilter] = useState({ publishers: [], categories: [] });
  const [compareGroups, setCompareGroups] = useState([{ key: "전체", label: "전체" }]);

  const [chartSelection, setChartSelection] = useState({
    selectedEmotions: [],
    timeseriesOpen: false,
  });

  const [selectedHeadline, setSelectedHeadline] = useState(null);

  const [toast, setToast] = useState(null);

  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  }, []);

  const applyFilter = useCallback((draft) => {
    setActiveFilter(draft);
    setCompareGroups(buildCompareGroups(draft));
    setChartSelection((s) => ({ ...s, selectedEmotions: [] }));
  }, []);

  const resetFilter = useCallback(() => {
    const empty = { publishers: [], categories: [] };
    setFilterDraft(empty);
    setActiveFilter(empty);
    setCompareGroups([{ key: "전체", label: "전체" }]);
    setChartSelection((s) => ({ ...s, selectedEmotions: [] }));
  }, []);

  return (
    <AppContext.Provider value={{
      dt, setDt,
      sentimentGroup, setSentimentGroup,
      filterDraft, setFilterDraft,
      activeFilter,
      compareGroups,
      applyFilter, resetFilter,
      chartSelection, setChartSelection,
      selectedHeadline, setSelectedHeadline,
      toast, showToast,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
