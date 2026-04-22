/**
 * Single export point for the TutorEngine instance.
 * Swap LocalEngine → RemoteEngine here when the backend lands.
 */
import { LocalEngine } from './local';
import type { TutorEngine } from '@/shared/api';

export const engine: TutorEngine = new LocalEngine();
