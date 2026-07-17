// Throwaway page to characterize the Turbopack JSX whitespace bug. DELETE ME.
export default function WsTest() {
  const x = 2026;
  return (
    <main>
      <p id="t2">
        B {x} tail that wraps onto another
        source line before ending.
      </p>
      <p id="t7">
        G {x} yet. The review fills in after a
        week&apos;s games finish and grading runs.
      </p>
      <p id="t14">
        N {x} yet. The review fills in after a
        week’s games finish and grading runs.
      </p>
      <p id="t15">
        O {x} yet — plain ascii wrap with an em dash
        in the tail but nothing else fancy.
      </p>
      <p id="t16">
        P <i>toward</i> us before kickoff — i.e. average line
        value rises with the size.
      </p>
    </main>
  );
}
