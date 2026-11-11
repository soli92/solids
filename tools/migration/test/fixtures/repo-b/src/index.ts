import { same } from './same';
import { divergent } from './divergent.js';
import { onlyB } from './only-b';
import { helper } from '@/util/helper';
import { missing } from './non-esiste';
export const run = () => [same(), divergent(), onlyB(), helper(), missing];
