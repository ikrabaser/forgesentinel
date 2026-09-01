/**
 * Renders the fixed backdrop behind every page (see index.css): a
 * faint technical grid plus a single soft, static vignette anchored
 * top-left. Deliberately static, not drifting color blobs - a
 * premium industrial console should read as calm and precise, not
 * animated for its own sake. Mounted once at the app root, behind
 * everything (z-0), so every page sits on the same backdrop rather
 * than each page re-implementing its own.
 */
export function BackgroundFX() {
  return (
    <>
      <div className="background-vignette" aria-hidden />
      <div className="background-grid" aria-hidden />
    </>
  );
}
