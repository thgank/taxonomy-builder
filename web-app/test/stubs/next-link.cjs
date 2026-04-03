const React = require("react");

function Link(props) {
  const {
    href,
    children,
    scroll,
    ...rest
  } = props;

  return React.createElement(
    "a",
    {
      href: typeof href === "string" ? href : String(href),
      "data-scroll": scroll === undefined ? undefined : String(scroll),
      ...rest,
    },
    children,
  );
}

module.exports = Link;
module.exports.default = Link;
