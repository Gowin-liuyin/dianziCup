export interface GraphPoint { x: number; y: number }
export interface GraphEdgeCurve { edgeId: string; path: string; points: GraphPoint[] }

/** 当前有界图最多200节点；128段近似的屏幕误差在180%缩放下小于2px，由候选余量保留交点歧义。 */
export function createGraphEdgeCurve(edgeId: string, subject: GraphPoint, object: GraphPoint, index: number): GraphEdgeCurve {
  const first = { x: subject.x + 70, y: subject.y + 50 + index % 4 * 18 };
  const second = { x: object.x - 70, y: object.y + 50 + index % 4 * 18 };
  const points: GraphPoint[] = [];
  for (let step = 0; step <= 128; step += 1) {
    const fraction = step / 128;
    const remaining = 1 - fraction;
    points.push({
      x: remaining ** 3 * subject.x + 3 * remaining ** 2 * fraction * first.x + 3 * remaining * fraction ** 2 * second.x + fraction ** 3 * object.x,
      y: remaining ** 3 * subject.y + 3 * remaining ** 2 * fraction * first.y + 3 * remaining * fraction ** 2 * second.y + fraction ** 3 * object.y,
    });
  }
  return { edgeId, path: `M${subject.x} ${subject.y} C${first.x} ${first.y},${second.x} ${second.y},${object.x} ${object.y}`, points };
}

function distanceToSegment(point: GraphPoint, start: GraphPoint, end: GraphPoint): number {
  const horizontal = end.x - start.x;
  const vertical = end.y - start.y;
  const lengthSquared = horizontal ** 2 + vertical ** 2;
  const fraction = lengthSquared === 0 ? 0 : Math.max(0, Math.min(1, ((point.x - start.x) * horizontal + (point.y - start.y) * vertical) / lengthSquared));
  return Math.hypot(point.x - start.x - fraction * horizontal, point.y - start.y - fraction * vertical);
}

/** 在CSS像素中选最近可见曲线；近似并列全部交由用户确认，不信任后绘透明path的DOM目标。 */
export function findGraphEdgeCandidates(curves: readonly GraphEdgeCurve[], point: GraphPoint, pixelsPerUnit: number): string[] {
  if (!Number.isFinite(pixelsPerUnit) || pixelsPerUnit <= 0 || !Number.isFinite(point.x) || !Number.isFinite(point.y)) return [];
  const distances = curves.map((curve) => {
    let distance = Number.POSITIVE_INFINITY;
    for (let index = 1; index < curve.points.length; index += 1) {
      const start = curve.points[index - 1]; const end = curve.points[index];
      if (start && end) distance = Math.min(distance, distanceToSegment(point, start, end) * pixelsPerUnit);
    }
    return { edgeId: curve.edgeId, distance };
  }).sort((left, right) => left.distance - right.distance || left.edgeId.localeCompare(right.edgeId));
  const closest = distances[0];
  if (!closest || closest.distance > 24) return [];
  return distances.filter((item) => item.distance <= 24 && item.distance <= closest.distance + 4).map((item) => item.edgeId);
}
