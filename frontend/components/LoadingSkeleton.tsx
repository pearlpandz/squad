type SkeletonVariant = "rows" | "cards" | "details" | "form" | "chat" | "content";

export function LoadingSkeleton({ variant = "rows", count = 3, label = "Loading page", fullPage = false, header = false }: {
  variant?: SkeletonVariant;
  count?: number;
  label?: string;
  fullPage?: boolean;
  header?: boolean;
}) {
  return <div className={`${fullPage ? "projectPage " : ""}loadingSkeleton loadingSkeleton--${variant}`} aria-busy="true">
    <span className="skeletonStatus" role="status">{label}…</span>
    {(header || fullPage) && <div className="skeletonHeader" aria-hidden="true">
      <span className="skeletonBlock skeletonTitle" />
      <span className="skeletonBlock skeletonSubtitle" />
    </div>}
    <div className="skeletonItems" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => <div className="skeletonItem" key={index}>
        <span className="skeletonBlock skeletonAvatar" />
        <div className="skeletonLines">
          <span className="skeletonBlock skeletonLine skeletonLineTitle" />
          <span className="skeletonBlock skeletonLine" />
          <span className="skeletonBlock skeletonLine skeletonLineShort" />
        </div>
        <span className="skeletonBlock skeletonAction" />
      </div>)}
    </div>
  </div>;
}
