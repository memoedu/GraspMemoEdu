const disabledFeaturesSwitch = '--disable-features=';
const lockoutWorkaround = ['AutofillAiWalletPrivatePasses', 'AutofillAmbientAutofill'];

export async function launchAcceptanceChrome(requirePlaywright) {
  const {chromium} = requirePlaywright('playwright');
  const options = {channel: 'chrome', headless: true};
  if (process.platform !== 'win32') return chromium.launch(options);

  // Preserve Playwright's defaults in a single switch. Chromium can overwrite
  // the default list when the command line supplies this switch twice.
  const {server} = requirePlaywright('playwright-core/lib/coreBundle');
  const defaults = await server.createPlaywright({sdkLanguage: 'javascript'})
    .chromium.defaultArgs(options, false, '');
  const defaultSwitch = defaults.find(arg => arg.startsWith(disabledFeaturesSwitch));
  const defaultFeatures = defaultSwitch?.slice(disabledFeaturesSwitch.length).split(',') ?? [];
  const mergedFeatures = [...new Set([...defaultFeatures, ...lockoutWorkaround])];
  return chromium.launch({
    ...options,
    ignoreDefaultArgs: defaultSwitch ? [defaultSwitch] : [],
    // https://issues.chromium.org/issues/541310282
    args: [disabledFeaturesSwitch + mergedFeatures.join(',')],
  });
}
