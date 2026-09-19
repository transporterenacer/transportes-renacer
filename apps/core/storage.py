from whitenoise.storage import CompressedManifestStaticFilesStorage


class WhiteNoiseNonStrictStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False
