/**
 * One-time app startup: read/create student id, prime the derived cache.
 * Returns `ready` so App.tsx can gate on data being loaded.
 */
import { useEffect, useState } from 'react';
import { useTutor } from './tutor';
import { getOrCreateStudentId } from './persist';

export function useBootstrap(): boolean {
  const [ready, setReady] = useState(false);
  const setStudentId = useTutor((s) => s.setStudentId);
  const refresh = useTutor((s) => s.refresh);

  useEffect(() => {
    (async () => {
      const sid = await getOrCreateStudentId();
      setStudentId(sid);
      await refresh();
      setReady(true);
    })();
  }, [setStudentId, refresh]);

  return ready;
}
