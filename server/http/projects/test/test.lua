local cjson = require("cjson");
local redis = require("resty.redis");
local tm = require("test_module");
local misc = require("misc");


local main = function ()
    local rsp = {};

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
    ngx.say("hello ", data);

    local args, err = ngx.req.get_post_args();
    if table.is_empty(args) then
        ngx.log(ngx.DEBUG, "failed to get post args:", err);
        return;
    end

    ngx.say("method:" .. ngx.req.get_method());
    ngx.say("sum:" .. tm.sum(2, 3));
    for key, val in pairs(args) do
        if type(val) == "table" then
            ngx.log(ngx.DEBUG, key, ": ", table.concat(val, ", "));
        else
            ngx.log(ngx.DEBUG, key, ": ", val);
        end
    end
end


main();
