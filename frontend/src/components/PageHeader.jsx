export default function PageHeader({ title, chip, children }) {
  return (
    <header className="h-14 flex-shrink-0 bg-white border-b hairline px-5 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h1 className="text-[15px] font-semibold tracking-tight">{title}</h1>
        {chip && (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border hairline text-neutral-500">{chip}</span>
        )}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </header>
  );
}
