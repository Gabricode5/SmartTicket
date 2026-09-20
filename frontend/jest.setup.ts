import "@testing-library/jest-dom";

// jsdom n'implémente ni scrollIntoView ni la pointer capture API -- Radix UI (Select,
// notamment) les appelle en interne dès qu'on ouvre un menu déroulant et clique une
// option, ce qui plante tout test interagissant réellement avec un <Select> (ex. le
// sélecteur de pôle, feature/poles). Polyfills no-op globaux, sans effet en prod.
if (typeof Element !== "undefined") {
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
}
