export default function Header({ activeTab, onTabChange }) {
  return (
    <header className="sticky top-0 z-40 bg-[#faf9f5] border-b border-gray-200 shadow-sm">
      <div className="max-w-[1280px] mx-auto px-6 h-14 flex items-center justify-between">
        <span className="font-semibold text-[#1B365D] text-lg tracking-tight">
          뉴스 감정 모니터링
        </span>
        <nav className="flex gap-1">
          {["모니터링", "헤드라인 탐색"].map((tab) => (
            <button
              key={tab}
              onClick={() => onTabChange(tab)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                activeTab === tab
                  ? "bg-[#1B365D] text-white"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
}
