# Browser imports

The Chrome extension and Firefox add-on send the active tab or all tabs in
the current window to the toolkit. Downloads and uploads run in the toolkit
process. Supported pages and authentication depend on
[gallery-dl import support](importing.md#import-from-a-url).

## Start the local webserver

Install and [configure the toolkit](setup.md#connect-to-szurubooru) on the
computer running the browser, then start the server.

```sh
szuru-toolkit webserver
```

The bundled extensions connect to `http://127.0.0.1:5000`. Keep the server
on loopback for browser use. The CLI has `--host` and `--port` options.
Changing the port also requires updating the extension's endpoint and
host permissions. Use a browser-specific configuration with
`queue_path` omitted.

## Install the extension

- **Chrome.** Open `chrome://extensions/`, enable **Developer mode**,
  select **Load unpacked** and choose the
  [chrome_extension](../chrome_extension/) directory.
- **Firefox.** Install a signed `.xpi` through the Add-ons Manager if you have
  one. To try the version from this repository, open
  `about:debugging#/runtime/this-firefox`, select **Load Temporary Add-on**
  and choose [firefox_addon/manifest.json](../firefox_addon/manifest.json).
  Firefox unloads a temporary add-on when the browser restarts.

## Import a tab

Open the extension popup and choose **Import current tab** or **Import all
tabs**. The second option uses the tabs in the current window.

The popup has optional fields for a cookie file path and a media range such as
`1-10`. It remembers those values between uses. A blank field uses the
corresponding value in the toolkit configuration. The cookie file path must
be readable by the process that runs the webserver.

For a failed import, check that the server is running on
`127.0.0.1:5000`, then check the toolkit output. It can distinguish a
download error from a booru connection or permission error. Once the
toolkit accepts the request, processing can continue if the browser stops
waiting for the response.
