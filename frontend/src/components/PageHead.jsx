import React from "react";

export default function PageHead({ eyebrow, title, sub, children }) {
  return (
    <div className="page-head spread">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {children}
    </div>
  );
}
