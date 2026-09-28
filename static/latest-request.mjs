export function createLatestRequestGate() {
  let generation = 0;
  return {
    begin() {
      generation += 1;
      const requestGeneration = generation;
      return () => requestGeneration === generation;
    },
  };
}
