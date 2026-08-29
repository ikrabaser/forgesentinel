/**
 * Renders the fixed animated glow + grid backdrop (see index.css).
 * Mounted once at the app root, behind everything (z-0), so every
 * page sits on the same living background rather than each page
 * re-implementing its own.
 */
export function BackgroundFX() {
  return (
    <>
      <div className="background-fx" aria-hidden>
        <span className="fx-blob-3" />
      </div>
      <div className="background-grid" aria-hidden />
    </>
  );
}
