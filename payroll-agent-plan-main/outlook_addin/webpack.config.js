/* eslint-disable no-undef */

const path = require("path");
const devCerts = require("office-addin-dev-certs");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const webpack = require("webpack");

require("dotenv").config({ path: path.resolve(__dirname, ".env") });

const urlDev = "https://localhost:3000/";
// Production static host for the task pane (e.g. Azure Static Web Apps). Must end with "/".
const urlProd = process.env.ADDIN_PROD_URL || "https://localhost:3000/";

// Only these keys are inlined into the bundle (see src/config.ts).
const PUBLIC_ENV_KEYS = [
  "VITE_AUTH_DISABLED",
  "VITE_ENTRA_CLIENT_ID",
  "VITE_ENTRA_TENANT_ID",
  "VITE_ENTRA_API_SCOPE",
  "VITE_API_BASE_URL",
  "VITE_QUEUE_MAILBOX",
  "VITE_DEV_SPECIALIST_ID",
];

function publicEnv() {
  const env = {};
  for (const key of PUBLIC_ENV_KEYS) {
    env[key] = process.env[key] || "";
  }
  return env;
}

async function getHttpsOptions() {
  const httpsOptions = await devCerts.getHttpsServerOptions();
  return { ca: httpsOptions.ca, key: httpsOptions.key, cert: httpsOptions.cert };
}

module.exports = async (env, options) => {
  const dev = options.mode === "development";
  const config = {
    devtool: "source-map",
    entry: {
      polyfill: ["core-js/stable", "regenerator-runtime/runtime"],
      react: ["react", "react-dom"],
      taskpane: {
        import: ["./src/taskpane/index.tsx", "./src/taskpane/taskpane.html"],
        dependOn: "react",
      },
      dialog: "./src/auth/dialog.ts",
    },
    output: {
      clean: true,
    },
    resolve: {
      extensions: [".ts", ".tsx", ".html", ".js"],
    },
    module: {
      rules: [
        {
          test: /\.ts$/,
          exclude: /node_modules/,
          use: {
            loader: "babel-loader",
          },
        },
        {
          test: /\.tsx?$/,
          exclude: /node_modules/,
          use: ["ts-loader"],
        },
        {
          // *.module.css → CSS modules (same convention as web/); other .css is global.
          test: /\.css$/,
          use: [
            "style-loader",
            {
              loader: "css-loader",
              options: {
                modules: {
                  auto: true,
                  namedExport: false,
                  exportLocalsConvention: "as-is",
                  localIdentName: "[name]__[local]--[hash:base64:5]",
                },
              },
            },
          ],
        },
        {
          test: /\.html$/,
          exclude: /node_modules/,
          use: "html-loader",
        },
        {
          test: /\.(png|jpg|jpeg|ttf|woff|woff2|gif|ico)$/,
          type: "asset/resource",
          generator: {
            filename: "assets/[name][ext][query]",
          },
        },
      ],
    },
    plugins: [
      new webpack.DefinePlugin({
        __ADDIN_ENV__: JSON.stringify(publicEnv()),
      }),
      new HtmlWebpackPlugin({
        filename: "taskpane.html",
        template: "./src/taskpane/taskpane.html",
        chunks: ["polyfill", "taskpane", "react"],
      }),
      new HtmlWebpackPlugin({
        filename: "dialog.html",
        template: "./src/auth/dialog.html",
        chunks: ["polyfill", "dialog"],
      }),
      new CopyWebpackPlugin({
        patterns: [
          {
            from: "assets/*",
            to: "assets/[name][ext][query]",
          },
          {
            from: "manifest*.json",
            to: "[name]" + "[ext]",
            transform(content) {
              if (dev) {
                return content;
              } else {
                return content.toString().replace(new RegExp(urlDev, "g"), urlProd);
              }
            },
          },
        ],
      }),
      new webpack.ProvidePlugin({
        Promise: ["es6-promise", "Promise"],
      }),
    ],
    devServer: {
      hot: true,
      headers: {
        "Access-Control-Allow-Origin": "*",
      },
      server: {
        type: "https",
        options: env.WEBPACK_BUILD || options.https !== undefined ? options.https : await getHttpsOptions(),
      },
      port: process.env.npm_package_config_dev_server_port || 3000,
      // Local backend is plain http on :8088; proxying avoids mixed content and CORS in dev.
      proxy: [
        {
          context: ["/api"],
          target: process.env.ADDIN_DEV_API_TARGET || "http://127.0.0.1:8088",
          changeOrigin: true,
          pathRewrite: { "^/api": "" },
        },
      ],
    },
  };

  return config;
};
