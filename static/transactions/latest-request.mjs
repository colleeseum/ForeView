// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

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
