local cjson = require("cjson");
local redis = require("resty.redis");
local misc = require("misc");


local main = function ()
    local rsp = {};

    ngx.header["Access-Control-Allow-Origin"] = "*";
    if "POST" ~= ngx.req.get_method() then
        rsp["result"] = "405";
        rsp["message"] = "method not allowed";
        ngx.print(cjson.encode(rsp));
        return;
    end

    local h = ngx.req.get_headers()
    for k, v in pairs(h) do
        ngx.log(ngx.DEBUG, k, ": ", v);
    end

    local data = ngx.req.get_body_data();

    local args, err = ngx.req.get_post_args();
    if table.is_empty(args) then
        ngx.log(ngx.DEBUG, "failed to get post args:", err);
        rsp["result"] = "406";
        rsp["message"] = "missing arguments";
        ngx.print(cjson.encode(rsp));
        return;
    end

    local sessionid = args["sessionid"];
    ngx.log(ngx.DEBUG, "delete session:" .. sessionid);

    rsp["result"] = "200";
    rsp["message"] = "success";
    ngx.print(cjson.encode(rsp));
end


main();
