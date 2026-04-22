/**
 * AsyncStorage-backed event log. Append-only, replay is the source of truth.
 * Keys are scoped per student so multiple profiles could coexist later.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { LogEvent, StudentId } from '@/shared/types';

const LOG_KEY = (sid: StudentId) => `ogrendiem:log:${sid}`;
const SID_KEY = 'ogrendiem:student_id';

export async function loadLog(studentId: StudentId): Promise<LogEvent[]> {
  const raw = await AsyncStorage.getItem(LOG_KEY(studentId));
  if (!raw) return [];
  try {
    return JSON.parse(raw) as LogEvent[];
  } catch {
    return [];
  }
}

export async function appendEvent(studentId: StudentId, ev: LogEvent): Promise<void> {
  const log = await loadLog(studentId);
  log.push(ev);
  await AsyncStorage.setItem(LOG_KEY(studentId), JSON.stringify(log));
}

export async function resetLog(studentId: StudentId): Promise<void> {
  await AsyncStorage.removeItem(LOG_KEY(studentId));
}

// ---------- student id ----------

function uuid(): string {
  // RFC4122-ish; good enough for anonymous local id. Backend will adopt it.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export async function getOrCreateStudentId(): Promise<StudentId> {
  const existing = await AsyncStorage.getItem(SID_KEY);
  if (existing) return existing;
  const fresh = uuid();
  await AsyncStorage.setItem(SID_KEY, fresh);
  return fresh;
}
