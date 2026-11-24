const disabledFeaturesSwitch = '--disable-features=';
const lockoutWorkaround = ['AutofillAiWalletPrivatePasses', 'AutofillAmbientAutofill'];

export async function launchAcceptanceChrome(requirePlaywright, args = [], {profile, ...contextOptions} = {}) {
  const {chromium} = requirePlaywright('playwright');
  const options = {channel: 'chrome', headless: true, args};
  const launch = settings => profile
    ? chromium.launchPersistentContext(profile, {...settings, ...contextOptions})
    : chromium.launch(settings);
  if (process.platform !== 'win32') return launch(options);

  // Preserve Playwright's defaults in a single switch. Chromium can overwrite
  // the default list when the command line supplies this switch twice.
  const {server} = requirePlaywright('playwright-core/lib/coreBundle');
  const defaults = await server.createPlaywright({sdkLanguage: 'javascript'})
    .chromium.defaultArgs(options, Boolean(profile), profile || '');
  const defaultSwitch = defaults.find(arg => arg.startsWith(disabledFeaturesSwitch));
  const defaultFeatures = defaultSwitch?.slice(disabledFeaturesSwitch.length).split(',') ?? [];
  const mergedFeatures = [...new Set([...defaultFeatures, ...lockoutWorkaround])];
  return launch({
    ...options,
    ignoreDefaultArgs: defaultSwitch ? [defaultSwitch] : [],
    // https://issues.chromium.org/issues/541310282
    args: [...args, disabledFeaturesSwitch + mergedFeatures.join(',')],
  });
}
