/**
 * Bundled static content loaded synchronously from assets/data/*.json.
 * Later, RemoteEngine will fetch these same shapes from /api/static/*.
 */
import type { Cluster, Edge, Question, Topic, TopicId } from '@/shared/types';

// Metro bundles JSON as import at build time.
import topicsJson from '../../assets/data/topics.json';
import graphJson from '../../assets/data/graph.json';
import clustersJson from '../../assets/data/clusters.json';
import questionsJson from '../../assets/data/questions.json';

interface TopicsFile {
  meta: { scope: string; chapters: number[]; n_topics: number; n_edges: number };
  topics: Topic[];
}
interface GraphFile {
  nodes: TopicId[];
  edges: Edge[];
}
interface ClustersFile {
  clusters: Cluster[];
}

export const topics: Topic[] = (topicsJson as unknown as TopicsFile).topics;
export const meta = (topicsJson as unknown as TopicsFile).meta;
export const graph: GraphFile = graphJson as unknown as GraphFile;
export const clusters: Cluster[] = (clustersJson as unknown as ClustersFile).clusters;
export const questions: Question[] = questionsJson as unknown as Question[];

// Indexes for O(1) lookup.
export const topicById: Record<TopicId, Topic> = Object.fromEntries(
  topics.map((t) => [t.topic_id, t]),
);

export const parentsOf: Record<TopicId, TopicId[]> = (() => {
  const m: Record<TopicId, TopicId[]> = {};
  for (const t of topics) m[t.topic_id] = [];
  for (const e of graph.edges) {
    if (m[e.to]) m[e.to].push(e.from);
  }
  return m;
})();

export const childrenOf: Record<TopicId, TopicId[]> = (() => {
  const m: Record<TopicId, TopicId[]> = {};
  for (const t of topics) m[t.topic_id] = [];
  for (const e of graph.edges) {
    if (m[e.from]) m[e.from].push(e.to);
  }
  return m;
})();

export const clusterById: Record<number, Cluster> = Object.fromEntries(
  clusters.map((c) => [c.cluster_id, c]),
);

export const questionsByTopic: Record<TopicId, Question[]> = (() => {
  const m: Record<TopicId, Question[]> = {};
  for (const q of questions) {
    (m[q.topic_id] ??= []).push(q);
  }
  return m;
})();

export function chaptersInScope(): string[] {
  return Array.from(new Set(topics.map((t) => t.parent_chapter_num))).sort();
}
