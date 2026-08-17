export default function Loading() {
  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <div className="space-y-2">
          <div className="h-8 w-48 skeleton rounded" />
          <div className="h-4 w-64 skeleton rounded" />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="kpi-card">
            <div className="h-4 w-24 skeleton rounded mb-3" />
            <div className="h-8 w-32 skeleton rounded" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <div className="h-80 skeleton rounded-xl" />
        <div className="h-80 skeleton rounded-xl" />
      </div>
    </div>
  );
}
