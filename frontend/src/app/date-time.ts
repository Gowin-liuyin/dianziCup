/** Present validated timestamps in the project's fixed Beijing reporting offset. */
export function formatShanghaiTimestamp(value: string): string {
  return new Date(Date.parse(value) + 8 * 60 * 60 * 1000).toISOString().replace(/\.\d{3}Z$/, "+08:00");
}
