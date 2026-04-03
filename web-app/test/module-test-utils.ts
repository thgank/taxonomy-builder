type MockExports = Record<string, unknown>;

export function clearModule(modulePath: string) {
  const resolved = require.resolve(modulePath);
  delete require.cache[resolved];
}

export function mockModule(modulePath: string, exports: MockExports) {
  const resolved = require.resolve(modulePath);
  require.cache[resolved] = {
    id: resolved,
    filename: resolved,
    loaded: true,
    exports,
  } as unknown as NodeJS.Module;
}

export function importFresh<T>(modulePath: string): T {
  clearModule(modulePath);
  return require(modulePath) as T;
}

export function restoreModules(modulePaths: string[]) {
  for (const modulePath of modulePaths) {
    clearModule(modulePath);
  }
}
