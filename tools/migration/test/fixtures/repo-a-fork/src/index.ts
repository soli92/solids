import { same } from './same';
import { divergent } from './divergent.js';
import { onlyA } from './only-a';
import { helper } from '@/util/helper';
// import { ghost } from './commentato';  <- nei commenti: non e' un import
export const run = () => [same(), divergent(), onlyA(), helper()];
