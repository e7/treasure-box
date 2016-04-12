table.is_empty = function (t)
    if t and next(t) then
        return false;
    else
        return true;
    end
end
