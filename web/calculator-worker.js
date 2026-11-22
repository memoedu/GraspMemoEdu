import {calculate, CalculationError} from './calculator-engine.js?v=dd33b5c7c0ee5ea2';

self.onmessage = async ({data}) => {
  try {
    self.postMessage({result: await calculate(data)});
  } catch (error) {
    self.postMessage({error: error instanceof CalculationError ? error.code : 'invalid'});
  }
};
